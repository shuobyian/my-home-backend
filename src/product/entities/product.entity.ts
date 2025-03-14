import { Material } from 'src/material/entities/material.entity';
import { Category } from 'src/product/type/Category';
import { Tool } from 'src/product/type/Tool';
import {
  Column,
  Entity,
  JoinColumn,
  OneToMany,
  PrimaryGeneratedColumn,
} from 'typeorm';

@Entity('product', { schema: 'public' })
export class Product {
  @PrimaryGeneratedColumn({ type: 'integer', name: 'id' })
  id: number;

  @Column('varchar', { unique: true, name: 'name', length: 255 })
  name: string;

  @Column('integer', { name: 'level' })
  level: number;

  @Column('integer', { name: 'craftingPrice' })
  craftingPrice: number;

  @Column('varchar', { name: 'tool', length: 255 })
  tool: Tool;

  @Column('varchar', { name: 'category', length: 255 })
  category: Category;

  @OneToMany(() => Material, (material) => material.product)
  @JoinColumn([{ name: 'product_id', referencedColumnName: 'id' }])
  materials: Material[];
}
